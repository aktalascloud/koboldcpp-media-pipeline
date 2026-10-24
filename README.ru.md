# Медиапайплайн KoboldCpp MOSS
[English](README.md) · **[Скачать комплект Windows](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest)** · [API / OWUI](docs/API.md) · [Установка моделей](docs/MODELS.md) · [Лицензии](docs/LICENSES.md)

Портативная генерация фото и музыки через **[наш оптимизированный KoboldCpp](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa)**, форк [оригинального KoboldCpp](https://github.com/LostRuins/koboldcpp). Проверено на Haswell AVX2 и RX 580 Polaris/gfx803 8 ГБ. Backend остаётся Kobold; прокси предоставляет AUTOMATIC1111/OpenAI Images API, переключение моделей, лица, восстановление и Helaman 4×.

## Результаты MOSS
Использованы сохранённые тесты: для публикации ничего не генерировалось и не ретушировалось. [Происхождение пикселей](examples/gallery.json).

| Normal, лица + Gater | Часовщик, сохранённые 704×1056 | Ночь, сохранённые 704×1056 |
|---|---|---|
| [![Normal](examples/normal-moss.png)](examples/normal-moss.png) | [![Часовщик](examples/watchmaker-moss.png)](examples/watchmaker-moss.png) | [![Ночь](examples/night-moss.png)](examples/night-moss.png) |
| ![Лицо](examples/normal-moss-face.png) | ![Лицо](examples/watchmaker-moss-face.png) | ![Лицо](examples/night-moss-face.png) |

### High до обработки и после полного 4×
RGB исходника совпадает с базовым кадром измеренного High. Справа — лица, Gater и Helaman, поэтому это сравнение всей цепочки, а не только SR. Кропы сохраняют пиксели без масштабирования. Обзор справа уменьшен для страницы; ссылка открывает оригинальный PNG 3712×5568.

| Native 928×1392 | Лица + Gater + Helaman 4× |
|---|---|
| [![Исходник](examples/high-native-moss.png)](examples/high-native-moss.png) | [![Превью 4×](examples/high-4x-preview.png)](examples/high-4x-moss.png) |
| ![Глаза](examples/high-native-moss-eyes.png) | ![Глаза](examples/high-4x-moss-eyes.png) |
| ![Лицо](examples/high-native-moss-face.png) | ![Лицо](examples/high-4x-moss-face.png) |

## Настройки и время
| Режим | Native, строго 2:3 | Шаги / кэш | Результат | Полный запрос |
|---|---|---|---|---:|
| Normal / бюджет редактирования | 736×1104 | 8 / Cache-DiT 0,08 | Лица + Gater, без автоSR | **141,47 с** |
| High | 928×1392, 1,29 МП | 8 / Cache-DiT 0,08 | Лица + Gater + 4×, 3712×5568 | **861,79 с — 14 минут 22 секунды** |

High измерен одним запросом, включая переключение профиля. Native — 245,676 с; лица — 1,597 с; Gater — 4,608 с; Helaman — 588,394 с; остаток — переключение и передача PNG. OOM не было. Это один сохранённый сложный сюжет/seed, а не гарантированное время любого запроса. [Доказательства и границы замера](benchmarks/results.json). Эти цифры относятся к медиапрофилю; сравнение исходного и последнего native-билда находится в репозитории форка.

## Цепочка
1. Artius MOSS в совместимых image/text GGUF Q8_0, официальный tokenizer Qwen3.5 и FLUX2 VAE. Старые LoRA Z-Image и `physioshade` не используются. Исходная упаковка INT8/W4A8 преобразуется локально; конвертированные веса не публикуются.
2. Euler/simple, **8 шагов**, CFG 1, shift 5, clip skip −1, eta 0, Flash Attention. Cache-DiT: `threshold=0.08,warmup=4,Fn=16,Bn=2`. В контрольной сцене кэш пропустил два из восьми вычислений.
3. Энкодер — CPU, 20 потоков; генератор/VAE — Vulkan. Лимит High 6500 МиБ допускает сегментацию; выбранный размер помещался целым графом.
4. YuNet 960, порог 0,82; GPEN 512/OpenVINO CPU, смешивание 20%; SFace ≥0,97, до двух лиц. Размеры масштабируются автоматически: Normal 39–155 px, High 49–196 px. Крупное лицо может быть намеренно пропущено.
5. Gater Restore 1× FP32 DirectML получает полный кадр; sharpen выключен. Перед Gater/Helaman в High и отдельном SR освобождается VRAM Native; после ответа возвращается фото. После 4× нет повторных лиц/Gater. PNG-маркеры предотвращают повторную обработку.
6. Музыка загружается по API, возвращается в MP3, затем восстанавливается фото-модель в GPU. Видео отложено.

Чёткие глаза не гарантируют правильную анатомию и стрелки часов. Обработка может сгладить кожу/ткань; исходники доступны. Авторский TemporalScoreRescaling здесь не реализован. Q8 добавляет округление; идентичное исполнение ComfyUI не заявляется.

## Установка
Распакуйте **media-pipeline-code.zip**, один раз запустите **Setup.ps1**, затем пользуйтесь **Start.exe напрямую**. `Start.exe --check` проверяет комплект. Зависимости и модели скачиваются с закреплёнными SHA256; отдельной копии runtime нет. Во время первой установки нужно примерно 60 ГБ свободного места.

**Точный W4-энкодер:** файл Civitai **3313824**, SHA256 начинается с `b0a6c1ab29`. Нужен собственный доступ пользователя. Скачайте его со [страницы автора](https://civitai.com/models/3010191?modelVersionId=3416029) и запустите `Setup.ps1 -MossSourceDirectory <папка-загрузки>`. Альтернатива — ключ только в переменной процесса `CIVITAI_API_KEY`; установщик его не сохраняет и не печатает. Текущий HF v2 INT8 отличается и автоматически не подставляется. [Подробности](docs/MODELS.md).

GPEN скачивается у исходного ONNX-распространителя либо передаётся через `-GPENPath`; в новом code-релизе зеркала GPEN нет. Сохранена классификация **Non-Commercial**, полноценное исходное разрешение на распространение не заявляется. Большие веса MOSS/Qwen/AceStep не входят в Git и релиз.

По умолчанию public 5001/private 5003 доступны на loopback. Для другой машины OWUI явно укажите `-ListenHost 0.0.0.0` при Setup и настройте доступ своей сети. Автозапуск включается отдельно: **Start.exe --register-startup**. Native работает в отдельном видимом окне. Драйверы, BIOS, TDR и частоты не меняются. Старые LoRA/tokenizer Z-Image из общих ассетов не извлекаются.

Код обёртки — AGPL-3.0, поднабор GGUF — MIT; модели и runtime имеют собственные условия. Ключей, личных адресов, кэша, логов и PID/state в комплекте нет. [Лицензии компонентов](docs/LICENSES.md).
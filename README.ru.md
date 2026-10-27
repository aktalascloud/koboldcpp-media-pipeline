# KoboldCpp media pipeline · Dirty MOSS
[English](README.md) · [Windows-комплект](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest) · [API/OWUI](docs/API.md)

Переносимый фото/музыкальный API поверх [оптимизированного KoboldCpp](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa) и [оригинального KoboldCpp](https://github.com/LostRuins/koboldcpp). Haswell AVX2, RX580 Polaris/gfx8038GB.

**Dirty Q8 · Euler/simple ·8шагов ·CFG1 ·eta0 ·shift5.** Turbo dynamic69=1, Afterlight=0,25, Textslider=0,25. LoRA подключает сервер; trigger-слова не нужны. Normal/edit736×1104, High928×1392. Cache-DiT0,08/warmup4/Fn16/Bn2, FA. YuNet/GPEN/SFace/Gater и ClearReality4× сохранены. Normal без автоапскейла; `enable_hr:true` включает4×. High по умолчанию с4×. МузыкаMP3 по API с возвратом фото.

**155,60с — только генерация Normal**, одиночный прогон27октября на EXE `6b815fe4ace2`. Не включает загрузку, лица/Gater и SR. Кэш пропустил2/8, у DPM с теми же весами1/8 и178,87с. Полный цикл Dirty/High не замерялся; старые161,96с Refined к нему не относятся. [Все скалярные измерения](benchmarks/results.json).

![Полный рост, выбранная связка](examples/fullbody-native.png)

Галерея и сравнения — в [English README](README.md): полный рост выбранной связки; ночь/часовщик — отдельный контроль Dirty DPM/turbo без LoRA качества. Глаза, часы и анатомия могут содержать ошибки.

Разово `Setup.ps1 -MossSourceDirectory <папка-оригиналов>`, затем **Start.exe**. Нужны точный уменьшенный turbo и исходный текстовый энкодер; SHA/ссылки в [MODELS](docs/MODELS.md). Основные веса и LoRA не зеркалируются. Один runtime, отдельное видимое окно, автозапуск по желанию. Ограничения [редактирования](docs/EDITING.md) и [синтеза по описаниям референсов](docs/REFERENCE-SYNTHESIS.md) сохранены.

## English

On RX 580 and Haswell on 2026-11-18, the LightVAE-Pro worker went from 33.04 to 30.53 s for 17 saved Wan frames and from 81.53 to 76.47 s in one 49-frame pair. The new SA3 CPU worker processed three chunks of a 15-second effect in 21.57 s, down from 26.53 s. Outputs matched byte for byte. The code archive uses the existing pinned installer runtime, which keeps the compatible SA3 path.

## Русский

На RX 580 и Haswell 18.11.2026 LightVAE-Pro сократил время с 33,04 до 30,53 с на 17 сохранённых кадрах Wan и с 81,53 до 76,47 с на одной паре прогонов с 49 кадрами. Новый CPU-воркер SA3 обработал три чанка 15-секундного эффекта за 21,57 с вместо 26,53 с. Результаты совпали побайтно. Архив кода использует закреплённый рантайм установщика и сохраняет совместимый путь SA3.

[Runs and hashes / Замеры и хеши](results/lowlevel-media-20261118.json) · [Patches / Патчи](https://github.com/aktalascloud/koboldcpp-media-pipeline/tree/v2026.11.18-r1/patches)

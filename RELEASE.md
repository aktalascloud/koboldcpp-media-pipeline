## English

Haswell AVX2 and Polaris Vulkan · 2026-11-11. Stages FlashAttention K/V in shared memory, shortens AVX2 dot products and reuses YuE2 NAR scratch.

CPU decode 17.44 → 17.32 tok/s. YuE2 render 28.82 → 25.21 s. ABDM Normal + separate 4× 153.92 → 132.29 s by phase medians. Text, MP3, PCM and RGB matched. The CPU decode ranges overlap.

## Русский

Haswell AVX2 и Polaris Vulkan · 2026-11-11. FlashAttention переиспользует K/V в LDS. Ускорены AVX2 dot product и подготовка буферов NAR YuE2.

Декодирование на CPU 17.44 → 17.32 ток/с. Рендер YuE2 28.82 → 25.21 с. ABDM Normal + отдельный 4× 153.92 → 132.29 с по медианам этапов. Текст, MP3, PCM и RGB совпали. Диапазоны CPU-decode пересекаются.

[Timings / Замеры](results/performance-2026-11-11-kernels.json) · [Operations / Операции](results/operations-2026-11-11-kernels.json) · [PR diffs / Диффы](results/pr-review-2026-11-11-kernels.json) · [Native patches / Патчи](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa/tree/concedo_experimental/performance/patches/series).
